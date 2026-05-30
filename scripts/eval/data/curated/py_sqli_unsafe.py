import sqlite3
def handler(request, db):
    q = request.GET["q"]
    db.cursor().execute("SELECT * FROM u WHERE n='" + q + "'")  # SQLi: tainted concat
