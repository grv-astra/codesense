import sqlite3
def unsafe(request, db):
    q = request.GET["q"]
    db.cursor().execute("SELECT * FROM u WHERE n='" + q + "'")   # vulnerable line 4
def safe(request, db):
    q = request.GET["q"]
    db.cursor().execute("SELECT * FROM u WHERE n=?", (q,))       # safe line 7
