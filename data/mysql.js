import mysql from 'mysql2/promise';

let pool = null;
let isConnected = false;

export async function initMySQL() {
  const host = process.env.MYSQL_HOST;
  const user = process.env.MYSQL_USER;
  const password = process.env.MYSQL_PASSWORD;
  const database = process.env.MYSQL_DATABASE;
  const port = parseInt(process.env.MYSQL_PORT || '3306', 10);
  const dbUrl = process.env.DATABASE_URL;

  if (!host && !dbUrl) {
    console.log("[MySQL] No MYSQL_HOST or DATABASE_URL configured. Running in In-Memory Demo Mode.");
    return null;
  }

  try {
    const config = dbUrl ? dbUrl : {
      host,
      port,
      user,
      password,
      database,
      waitForConnections: true,
      connectionLimit: 10,
      queueLimit: 0
    };

    pool = mysql.createPool(config);

    // Test connection
    const conn = await pool.getConnection();
    console.log(`[MySQL] Successfully connected to MySQL 8.x database "${database || 'agricare'}".`);
    conn.release();

    // Initialize Schema
    await createTables();
    isConnected = true;
    return pool;
  } catch (err) {
    console.warn(`[MySQL] Unable to connect to MySQL (${err.message}). Falling back to In-Memory Demo Mode.`);
    pool = null;
    isConnected = false;
    return null;
  }
}

async function createTables() {
  if (!pool) return;

  const queries = [
    `CREATE TABLE IF NOT EXISTS users (
      user_id INT AUTO_INCREMENT PRIMARY KEY,
      name VARCHAR(100) NOT NULL,
      email VARCHAR(150) NOT NULL UNIQUE,
      password_hash VARCHAR(255) NOT NULL,
      phone VARCHAR(30) DEFAULT NULL,
      role VARCHAR(30) DEFAULT 'Farmer',
      created_at DATETIME DEFAULT CURRENT_TIMESTAMP
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;`,

    `CREATE TABLE IF NOT EXISTS user_profiles (
      profile_id INT AUTO_INCREMENT PRIMARY KEY,
      user_id INT NOT NULL,
      farm_name VARCHAR(150) DEFAULT NULL,
      location VARCHAR(200) DEFAULT NULL,
      email_verified BOOLEAN DEFAULT FALSE,
      phone_verified BOOLEAN DEFAULT FALSE,
      is_admin BOOLEAN DEFAULT FALSE,
      FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;`,

    `CREATE TABLE IF NOT EXISTS equipment (
      equipment_id INT AUTO_INCREMENT PRIMARY KEY,
      user_id INT NOT NULL,
      equipment_name VARCHAR(120) NOT NULL,
      equipment_type VARCHAR(60) NOT NULL,
      brand VARCHAR(80) DEFAULT NULL,
      model VARCHAR(80) DEFAULT NULL,
      year INT DEFAULT NULL,
      registration_number VARCHAR(50) DEFAULT NULL,
      purchase_date DATE DEFAULT NULL,
      operating_hours DECIMAL(10,2) DEFAULT 0.0,
      fuel_consumption DECIMAL(6,2) DEFAULT 0.0,
      usage_frequency VARCHAR(50) DEFAULT 'Daily',
      current_condition VARCHAR(50) DEFAULT 'Healthy',
      status VARCHAR(50) DEFAULT 'Healthy',
      location VARCHAR(120) DEFAULT NULL,
      created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
      FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;`,

    `CREATE TABLE IF NOT EXISTS maintenance (
      maintenance_id INT AUTO_INCREMENT PRIMARY KEY,
      equipment_id INT NOT NULL,
      service_date DATE NOT NULL,
      service_type VARCHAR(80) NOT NULL,
      problem_description TEXT DEFAULT NULL,
      action_taken TEXT DEFAULT NULL,
      parts_replaced VARCHAR(255) DEFAULT NULL,
      technician VARCHAR(100) DEFAULT NULL,
      cost DECIMAL(10,2) DEFAULT 0.0,
      next_service_date DATE DEFAULT NULL,
      status VARCHAR(30) DEFAULT 'Completed',
      created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
      FOREIGN KEY (equipment_id) REFERENCES equipment(equipment_id) ON DELETE CASCADE
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;`,

    `CREATE TABLE IF NOT EXISTS service_history (
      history_id INT AUTO_INCREMENT PRIMARY KEY,
      equipment_id INT NOT NULL,
      service_date DATE NOT NULL,
      service_type VARCHAR(80) NOT NULL,
      parts_replaced VARCHAR(255) DEFAULT NULL,
      cost DECIMAL(10,2) DEFAULT 0.0,
      technician VARCHAR(100) DEFAULT NULL,
      remarks TEXT DEFAULT NULL,
      created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
      FOREIGN KEY (equipment_id) REFERENCES equipment(equipment_id) ON DELETE CASCADE
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;`,

    `CREATE TABLE IF NOT EXISTS fuel_records (
      fuel_id INT AUTO_INCREMENT PRIMARY KEY,
      equipment_id INT NOT NULL,
      date DATE NOT NULL,
      fuel_quantity DECIMAL(8,2) NOT NULL,
      fuel_cost DECIMAL(10,2) NOT NULL,
      operating_hours DECIMAL(10,2) DEFAULT NULL,
      notes TEXT DEFAULT NULL,
      created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
      FOREIGN KEY (equipment_id) REFERENCES equipment(equipment_id) ON DELETE CASCADE
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;`,

    `CREATE TABLE IF NOT EXISTS bookings (
      booking_id INT AUTO_INCREMENT PRIMARY KEY,
      equipment_id INT NOT NULL,
      user_id INT NOT NULL,
      booking_date DATE NOT NULL,
      start_time VARCHAR(20) NOT NULL,
      end_time VARCHAR(20) NOT NULL,
      purpose VARCHAR(255) DEFAULT NULL,
      status VARCHAR(30) DEFAULT 'Confirmed',
      created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
      FOREIGN KEY (equipment_id) REFERENCES equipment(equipment_id) ON DELETE CASCADE,
      FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;`,

    `CREATE TABLE IF NOT EXISTS predictions (
      prediction_id INT AUTO_INCREMENT PRIMARY KEY,
      equipment_id INT NOT NULL,
      prediction_date DATETIME DEFAULT CURRENT_TIMESTAMP,
      condition_result VARCHAR(50) NOT NULL,
      risk_level VARCHAR(30) NOT NULL,
      probability DECIMAL(5,2) NOT NULL,
      recommendation TEXT DEFAULT NULL,
      explanation TEXT DEFAULT NULL,
      is_demo BOOLEAN DEFAULT TRUE,
      FOREIGN KEY (equipment_id) REFERENCES equipment(equipment_id) ON DELETE CASCADE
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;`,

    `CREATE TABLE IF NOT EXISTS notifications (
      notification_id INT AUTO_INCREMENT PRIMARY KEY,
      user_id INT NOT NULL,
      title VARCHAR(150) NOT NULL,
      message TEXT NOT NULL,
      notification_type VARCHAR(40) DEFAULT 'info',
      is_read BOOLEAN DEFAULT FALSE,
      created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
      FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;`
  ];

  for (const q of queries) {
    await pool.query(q);
  }
  console.log("[MySQL] All tables initialized and verified successfully.");
}

export function isMySQLConnected() {
  return isConnected;
}

export { pool };
