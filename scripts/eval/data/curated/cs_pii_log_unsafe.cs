public class UsersHandler
{
    public void Handler(User user)
    {
        // privacy: logs a raw SSN
        Console.WriteLine(user.CustomerSsn);
    }
}
