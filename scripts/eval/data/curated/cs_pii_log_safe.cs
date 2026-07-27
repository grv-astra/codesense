public class UsersHandler
{
    public void Handler(User user)
    {
        // safe: not personal data
        Console.WriteLine(user.OrderId);
    }
}
