from flask import Flask, jsonify, request
import time, requests, os
from jose import jwt
import json
import mysql.connector


REALM_NAME = "realm_524H0178"
# Internal URL — backend container resolves Keycloak via docker DNS để fetch JWKS
DISCOVERY_URL = f"http://authentication-identity-server:8080/realms/{REALM_NAME}"
JWKS_URL = f"{DISCOVERY_URL}/protocol/openid-connect/certs"

# Public issuer — phải khớp với `iss` claim trong token.
# Client (Postman/browser) gọi Keycloak qua URL nào thì Keycloak ghi iss bằng URL đó.
# Override qua biến môi trường OIDC_ISSUER khi deploy.
TOKEN_ISSUER = os.environ.get(
    "OIDC_ISSUER",
    f"http://authentication-identity-server:8080/realms/{REALM_NAME}",
)
AUDIENCE   = os.environ.get("OIDC_AUDIENCE", "flask-app")
# Với public client, `aud` có thể không chứa client_id → tắt verify_aud, chỉ kiểm `azp`
VERIFY_AUD = os.environ.get("OIDC_VERIFY_AUD", "false").lower() == "true"

_JWKS = None; _TS = 0
def get_jwks():
    global _JWKS, _TS
    now = time.time()
    if not _JWKS or now - _TS > 600:
        _JWKS = requests.get(JWKS_URL, timeout=5).json()
        _TS = now
    return _JWKS

app = Flask(__name__)


# ==================
# DATABSE CONNECTION
# ==================
def get_db():
    return mysql.connector.connect(
        host="relational-database-server",
        user="root",
        password="root",
        database="minicloud"
    )

def get_studentdb():
   return mysql.connector.connect(
       host="relational-database-server",
       user="root",
       password="root",
       database="studentdb"
)


@app.get("/hello")
def hello(): return jsonify(message="Hello from App Server!")

@app.get("/secure")
def secure():
    auth = request.headers.get("Authorization","")
    if not auth.startswith("Bearer "):
        return jsonify(error="Missing Bearer token"), 401
    token = auth.split(" ",1)[1]
    try:
        decode_kwargs = {
            "algorithms": ["RS256"],
            "issuer": TOKEN_ISSUER,
            "options": {"verify_aud": VERIFY_AUD},
        }
        if VERIFY_AUD:
            decode_kwargs["audience"] = AUDIENCE
        payload = jwt.decode(token, get_jwks(), **decode_kwargs)
        # Public client thường không có audience=flask-app, check azp thay thế
        if not VERIFY_AUD and payload.get("azp") != AUDIENCE:
            return jsonify(error=f"Invalid azp: {payload.get('azp')}"), 401
        return jsonify(
            message="Secure resource OK",
            preferred_username=payload.get("preferred_username"),
            issuer=payload.get("iss"),
            azp=payload.get("azp"),
        )
    except Exception as e:
        return jsonify(error=str(e)), 401

# =========================
# GET FROM DATABASE
# =========================
@app.get("/student")
def student():
    try:
        db = get_studentdb()
        cursor = db.cursor(dictionary=True)

        cursor.execute("SELECT student_id, fullname, dob, major FROM students")
        rows = cursor.fetchall()

        cursor.close()
        db.close()

        for row in rows:
            if row.get("dob"):
                row["dob"] = row["dob"].isoformat()

        return jsonify(rows)

    except mysql.connector.Error as err:
        return jsonify(message=f"Lỗi Database: {err.msg}"), 500

# =========================
# CREATE
# =========================
@app.post("/student")
def studentdb_create_student():
   data = request.get_json()
   if not data:
       return jsonify(message="Request body must be JSON"), 400
   
   required_fields = ["student_id", "fullname", "dob", "major"]
   for field in required_fields:
       if field not in data:
           return jsonify(message=f"Missing field: {field}"), 400

   db = get_studentdb()
   cursor = db.cursor()

   query = """
       INSERT INTO students (student_id, fullname, dob, major)
       VALUES (%s, %s, %s, %s)
   """
   values = (data["student_id"], data["fullname"], data["dob"], data["major"])

   try:
       cursor.execute(query, values)
       db.commit()
   except mysql.connector.Error as err:
       db.rollback()
       return jsonify(message=f"Database error: {err.msg}"), 500
   finally:
       cursor.close()
       db.close()

   return jsonify(message="Student created successfully"), 201


# =========================
# READ
# =========================
@app.get("/student/<string:student_id>")
def studentdb_get_student(student_id):
   db = get_studentdb()
   cursor = db.cursor(dictionary=True)

   try:
       cursor.execute(
           "SELECT student_id, fullname, dob, major FROM students WHERE student_id = %s",
           (student_id,),
       )
       student = cursor.fetchone()
   except mysql.connector.Error as err:
       return jsonify(message=f"Database error: {err.msg}"), 500
   finally:
       cursor.close()
       db.close()

   if student:
       # dob là DATE => convert sang string ISO cho đẹp
       if student.get("dob"):
           student["dob"] = student["dob"].isoformat()
       return jsonify(student)


   return jsonify(message="Student not found"), 404


# =========================
# UPDATE
# =========================
@app.put("/student/<string:student_id>")
def studentdb_update_student(student_id):
   data = request.get_json()
   if not data:
       return jsonify(message="Request body must be JSON"), 400


   required_fields = ["fullname", "dob", "major"]
   for field in required_fields:
       if field not in data:
           return jsonify(message=f"Missing field: {field}"), 400

   db = get_studentdb()
   cursor = db.cursor()

   query = """
       UPDATE students
       SET fullname = %s, dob = %s, major = %s
       WHERE student_id = %s
   """
   values = (data["fullname"], data["dob"], data["major"], student_id)

   try:
       cursor.execute(query, values)
       db.commit()
       affected_rows = cursor.rowcount
   except mysql.connector.Error as err:
       db.rollback()
       return jsonify(message=f"Database error: {err.msg}"), 500
   finally:
       cursor.close()
       db.close()


   if affected_rows == 0:
       return jsonify(message="Student not found"), 404


   return jsonify(message="Student updated successfully"), 200


# =========================
# DELETE
# =========================
@app.delete("/student/<string:student_id>")
def studentdb_delete_student(student_id):
   db = get_studentdb()
   cursor = db.cursor()
   try:
       cursor.execute("DELETE FROM students WHERE student_id = %s", (student_id,))
       db.commit()
       affected_rows = cursor.rowcount
   except mysql.connector.Error as err:
       db.rollback()
       return jsonify(message=f"Database error: {err.msg}"), 500
   finally:
       cursor.close()
       db.close()

   if affected_rows == 0:
       return jsonify(message="Student not found"), 404


   return jsonify(message="Student deleted successfully"), 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8081)