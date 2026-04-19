CREATE DATABASE IF NOT EXISTS studentdb;
USE studentdb;

CREATE TABLE IF NOT EXISTS students (
    student_id VARCHAR(20) PRIMARY KEY,
    fullname VARCHAR(100) NOT NULL,
    dob DATE,
    major VARCHAR(100)
);

INSERT INTO students (student_id, fullname, dob, major) VALUES 
('52400001', 'Nguyen Van A', '2004-05-15', 'Computer Science'),
('52400002', 'Tran Thi B', '2004-08-22', 'Information Technology');