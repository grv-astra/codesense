using System.Data.SqlClient;

public class UsersRepo
{
    public SqlCommand Find(SqlConnection conn, string id)
    {
        // safe: parameterized query, command text is a constant + bound parameter
        var cmd = new SqlCommand("SELECT * FROM Users WHERE Id = @id", conn);
        cmd.Parameters.AddWithValue("@id", id);
        return cmd;
    }
}
