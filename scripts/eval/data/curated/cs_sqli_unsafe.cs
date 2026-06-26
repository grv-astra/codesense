using System.Data.SqlClient;

public class UsersRepo
{
    public SqlCommand Find(SqlConnection conn, string id)
    {
        // SQLi: tainted user input concatenated into the SQL command text
        var cmd = new SqlCommand("SELECT * FROM Users WHERE Id = '" + id + "'", conn);
        return cmd;
    }
}
