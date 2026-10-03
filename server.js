const express = require('express');
const sqlite3 = require('sqlite3').verbose();
const multer = require('multer');
const path = require('path');
const fs = require('fs');

const app = express();
app.use(express.json());

// 1. Crear carpeta uploads si no existe
const dirUploads = path.join(__dirname, 'uploads');
if (!fs.existsSync(dirUploads)) {
  fs.mkdirSync(dirUploads, { recursive: true });
}

app.use('/uploads', express.static(dirUploads));
app.get('/estudiante', (req, res) => res.sendFile(path.join(__dirname, 'estudiante.html')));
app.get('/vigilante', (req, res) => res.sendFile(path.join(__dirname, 'vigilante.html')));

// 2. Subida de fotos
const storage = multer.diskStorage({
  destination: (req, file, cb) => cb(null, dirUploads),
  filename: (req, file, cb) => {
    const extension = path.extname(file.originalname);
    cb(null, `${Date.now()}-${Math.round(Math.random() * 1E9)}${extension}`);
  }
});
const upload = multer({ storage });

// 3. Conexión a Base de Datos SQLite
const db = new sqlite3.Database('./parqueadero.db', (err) => {
  if (err) console.error("Error DB:", err);
  else console.log("Base de datos 'parqueadero.db' lista.");
});

db.serialize(() => {
  // Tabla de Usuarios general (Estudiantes, Profesores, Admin, Visitantes)
  db.run(`CREATE TABLE IF NOT EXISTS usuarios (
    documento TEXT PRIMARY KEY,
    nombre TEXT NOT NULL,
    tipo_usuario TEXT NOT NULL, -- 'Estudiante', 'Profesor', 'Administrativo', 'Visitante'
    vinculacion TEXT NULL,     -- Carrera, Facultad o Área según el tipo
    password TEXT NOT NULL
  )`);

  db.run(`CREATE TABLE IF NOT EXISTS vehiculos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    documento_usuario TEXT,
    tipo TEXT,
    placa TEXT,
    color TEXT,
    detalles TEXT,
    foto_url TEXT,
    FOREIGN KEY(documento_usuario) REFERENCES usuarios(documento)
  )`);

  db.run(`CREATE TABLE IF NOT EXISTS accesos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    vehiculo_id INTEGER,
    hora_entrada DATETIME DEFAULT CURRENT_TIMESTAMP,
    hora_salida DATETIME NULL,
    FOREIGN KEY(vehiculo_id) REFERENCES vehiculos(id)
  )`);
});

// ------------------------------------------------------------------
// RUTAS DE USUARIOS Y AUTENTICACIÓN
// ------------------------------------------------------------------

// Registrar un nuevo usuario (Estudiante, Profesor, Admin, Visitante)
app.post('/api/usuario/registro', (req, res) => {
  const { documento, nombre, tipo_usuario, vinculacion, password } = req.body;
  if (!documento || !nombre || !tipo_usuario || !password) {
    return res.status(400).json({ error: "Campos requeridos incompletos." });
  }

  const sql = `INSERT INTO usuarios (documento, nombre, tipo_usuario, vinculacion, password) VALUES (?, ?, ?, ?, ?)`;
  db.run(sql, [documento, nombre, tipo_usuario, vinculacion || 'N/A', password], function(err) {
    if (err) return res.status(400).json({ error: "El documento o código ya está registrado." });
    res.json({ mensaje: "Registro exitoso. Puedes iniciar sesión." });
  });
});

// Iniciar Sesión
app.post('/api/usuario/login', (req, res) => {
  const { documento, password } = req.body;
  const sql = `SELECT documento, nombre, tipo_usuario, vinculacion FROM usuarios WHERE documento = ? AND password = ?`;

  db.get(sql, [documento, password], (err, user) => {
    if (err || !user) return res.status(401).json({ error: "Documento/Código o contraseña incorrectos." });
    res.json({ usuario: user });
  });
});

// Registrar un vehículo
app.post('/api/usuario/vehiculo', upload.single('foto'), (req, res) => {
  const { documento_usuario, tipo, placa, color, detalles } = req.body;
  const foto_url = req.file ? `/uploads/${req.file.filename}` : null;

  if (!documento_usuario || !tipo || !color) {
    return res.status(400).json({ error: "Faltan datos obligatorios." });
  }

  const sql = `INSERT INTO vehiculos (documento_usuario, tipo, placa, color, detalles, foto_url) VALUES (?, ?, ?, ?, ?, ?)`;
  db.run(sql, [documento_usuario, tipo, placa || 'Sin Placa', color, detalles, foto_url], function(err) {
    if (err) return res.status(500).json({ error: err.message });
    res.json({ mensaje: "Vehículo registrado con éxito" });
  });
});

// Obtener vehículos de un usuario
app.get('/api/usuario/mis-vehiculos/:documento', (req, res) => {
  const { documento } = req.params;
  db.all(`SELECT * FROM vehiculos WHERE documento_usuario = ?`, [documento], (err, rows) => {
    if (err) return res.status(500).json({ error: err.message });
    res.json({ vehiculos: rows });
  });
});

// Historial de accesos
app.get('/api/usuario/historial/:documento', (req, res) => {
  const { documento } = req.params;
  const sql = `
    SELECT a.id, v.tipo, v.placa, v.color, a.hora_entrada, a.hora_salida
    FROM accesos a
    JOIN vehiculos v ON a.vehiculo_id = v.id
    WHERE v.documento_usuario = ?
    ORDER BY a.hora_entrada DESC`;

  db.all(sql, [documento], (err, rows) => {
    if (err) return res.status(500).json({ error: err.message });
    res.json({ historial: rows });
  });
});

// ------------------------------------------------------------------
// RUTAS PARA EL VIGILANTE
// ------------------------------------------------------------------

// Buscar usuario y sus vehículos
app.get('/api/vigilante/buscar/:documento', (req, res) => {
  const { documento } = req.params;
  
  const sqlUsuario = `SELECT documento, nombre, tipo_usuario, vinculacion FROM usuarios WHERE documento = ?`;
  db.get(sqlUsuario, [documento], (err, usuario) => {
    if (err || !usuario) {
      return res.status(404).json({ error: "Usuario no registrado en el sistema." });
    }

    const sqlVehiculos = `SELECT * FROM vehiculos WHERE documento_usuario = ?`;
    db.all(sqlVehiculos, [documento], (err, vehiculos) => {
      if (err) return res.status(500).json({ error: err.message });
      res.json({ usuario, vehiculos });
    });
  });
});

app.post('/api/vigilante/entrada', (req, res) => {
  const { vehiculo_id } = req.body;
  db.run(`INSERT INTO accesos (vehiculo_id) VALUES (?)`, [vehiculo_id], function(err) {
    if (err) return res.status(500).json({ error: err.message });
    res.json({ mensaje: "Entrada registrada exitosamente." });
  });
});

app.put('/api/vigilante/salida', (req, res) => {
  const { vehiculo_id } = req.body;
  const sql = `UPDATE accesos SET hora_salida = CURRENT_TIMESTAMP WHERE vehiculo_id = ? AND hora_salida IS NULL`;
  db.run(sql, [vehiculo_id], function(err) {
    if (err) return res.status(500).json({ error: err.message });
    if (this.changes === 0) return res.status(404).json({ mensaje: "No hay una entrada activa para este vehículo." });
    res.json({ mensaje: "Salida registrada exitosamente." });
  });
});

const PUERTO = 3000;
app.listen(PUERTO, () => {
  console.log(`Servidor ejecutándose correctamente en http://localhost:${PUERTO}`);
});