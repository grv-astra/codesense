public class UsersHandler {
    void handler(User user) {
        // safe: not personal data
        System.out.println(user.orderId);
    }
}
