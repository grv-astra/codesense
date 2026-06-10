import sqlite3


def handler(request):
    q = request.GET["q"]
    conn = sqlite3.connect("db")
    conn.execute("SELECT * FROM users WHERE name = '" + q + "'")  # tainted concat
