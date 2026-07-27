<?php
function handler($user) {
    // safe: not personal data
    error_log($user->order_id);
}
