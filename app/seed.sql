-- OpsLens Realistic Enterprise Seed Data
-- Default password for all users: Password123!
-- Hash generated via Werkzeug scrypt

-- Roles
INSERT INTO roles (id, name, description) VALUES
(1, 'admin', 'System Administrator with full access to configuration, users, and audit logs'),
(2, 'agent', 'IT Support Specialist responsible for managing and resolving incident tickets'),
(3, 'requester', 'Standard employee capable of raising and tracking their own tickets');

-- Users
-- Password hash for 'Password123!'
INSERT INTO users (id, username, email, password_hash, role_id, is_active, created_at) VALUES
(1, 'admin', 'admin@opslens.local', 'scrypt:32768:8:1$7ufcFCmMHuQ9K6nu$e0169c553b5530a6a49657bbafc52bfab01936b63b6d7a578eee72cb064a00ec4091a55a37089f7e0a8b25cd0d0e6ebbe54697787b47d44542b32d0b24437417', 1, 1, '2026-09-01 08:00:00'),
(2, 'sarah_agent', 'sarah.support@opslens.local', 'scrypt:32768:8:1$7ufcFCmMHuQ9K6nu$e0169c553b5530a6a49657bbafc52bfab01936b63b6d7a578eee72cb064a00ec4091a55a37089f7e0a8b25cd0d0e6ebbe54697787b47d44542b32d0b24437417', 2, 1, '2026-09-01 08:30:00'),
(3, 'alex_agent', 'alex.support@opslens.local', 'scrypt:32768:8:1$7ufcFCmMHuQ9K6nu$e0169c553b5530a6a49657bbafc52bfab01936b63b6d7a578eee72cb064a00ec4091a55a37089f7e0a8b25cd0d0e6ebbe54697787b47d44542b32d0b24437417', 2, 1, '2026-09-01 09:00:00'),
(4, 'john_requester', 'john.doe@opslens.local', 'scrypt:32768:8:1$7ufcFCmMHuQ9K6nu$e0169c553b5530a6a49657bbafc52bfab01936b63b6d7a578eee72cb064a00ec4091a55a37089f7e0a8b25cd0d0e6ebbe54697787b47d44542b32d0b24437417', 3, 1, '2026-09-05 10:15:00'),
(5, 'emily_requester', 'emily.watson@opslens.local', 'scrypt:32768:8:1$7ufcFCmMHuQ9K6nu$e0169c553b5530a6a49657bbafc52bfab01936b63b6d7a578eee72cb064a00ec4091a55a37089f7e0a8b25cd0d0e6ebbe54697787b47d44542b32d0b24437417', 3, 1, '2026-09-05 11:20:00');

-- Categories
INSERT INTO categories (id, name, description) VALUES
(1, 'Network & Connectivity', 'Wi-Fi, VPN, firewall, DNS, and internal network infrastructure'),
(2, 'Hardware & Peripherals', 'Laptops, monitors, docking stations, and office printers'),
(3, 'Access & IAM', 'Account unlocks, role permissions, password resets, and MFA setup'),
(4, 'Software & Applications', 'Operating system bugs, enterprise tools, and email client issues'),
(5, 'Security & Compliance', 'Phishing reports, suspicious logins, malware alerts, and policy checks');

-- Sample Tickets
INSERT INTO tickets (id, title, description, category_id, priority, status, requester_id, assignee_id, created_at, updated_at, resolved_at) VALUES
(1, 'Corporate VPN Gateway Timeout during peak hours', 'Remote developers unable to connect to us-east gateway between 9 AM and 11 AM.', 1, 'high', 'in_progress', 4, 2, '2026-10-15 09:12:00', '2026-10-15 10:30:00', NULL),
(2, 'Suspicious phishing email reporting payroll update', 'Received an unsolicited email with an external OneDrive link claiming to be HR payroll change.', 5, 'critical', 'in_progress', 5, 2, '2026-10-15 11:05:00', '2026-10-15 11:45:00', NULL),
(3, 'MacBook Pro screen flickering and freezing', 'External monitor intermittently drops signal via USB-C dock after macOS update.', 2, 'medium', 'open', 4, 3, '2026-10-16 08:30:00', '2026-10-16 08:30:00', NULL),
(4, 'AWS Staging IAM Access Token Expired', 'Need read/write access to staging S3 bucket to verify data pipeline integration.', 3, 'high', 'resolved', 5, 3, '2026-10-16 14:00:00', '2026-10-16 16:30:00', '2026-10-16 16:30:00'),
(5, 'Corporate VPN Gateway Timeout in London Office', 'Second report of VPN connection handshake failure for remote team members.', 1, 'high', 'open', 5, 2, '2026-10-17 09:00:00', '2026-10-17 09:00:00', NULL),
(6, 'Excel macro crashing on launch for Finance team', 'Finance budget workbook gives runtime automation error 429 when refreshing pivot table.', 4, 'medium', 'resolved', 4, 2, '2026-10-17 10:15:00', '2026-10-17 12:45:00', '2026-10-17 12:45:00'),
(7, 'MFA Token Desynchronization for sales portal', 'Sales representative unable to log in after replacing mobile phone.', 3, 'medium', 'resolved', 4, 3, '2026-10-17 13:00:00', '2026-10-17 14:15:00', '2026-10-17 14:15:00'),
(8, 'Corporate VPN Gateway Timeout on mobile hotspots', 'Third incident regarding VPN gateway dropouts when roaming.', 1, 'high', 'open', 4, NULL, '2026-10-18 08:45:00', '2026-10-18 08:45:00', NULL),
(9, 'Unauthorized USB storage device plugged into workstation 14', 'DLP agent flagged an unapproved mass storage device connected to finance kiosk.', 5, 'critical', 'closed', 5, 2, '2026-10-18 10:00:00', '2026-10-18 12:00:00', '2026-10-18 12:00:00'),
(10, 'Request secondary monitor for dual-screen workflow', 'New hire ergonomics setup request for 27-inch 4K monitor.', 2, 'low', 'open', 5, NULL, '2026-10-18 15:30:00', '2026-10-18 15:30:00', NULL);

-- Ticket Comments
INSERT INTO ticket_comments (ticket_id, user_id, comment, is_internal, created_at) VALUES
(1, 2, 'Investigating gateway memory pressure. Increased tunnel pool allocation.', 1, '2026-10-15 09:45:00'),
(1, 4, 'Thanks Sarah, let me know when we can test again.', 0, '2026-10-15 10:00:00'),
(2, 2, 'Domain blocked at perimeter firewall. Submitted IOC hash to threat intel feed.', 1, '2026-10-15 11:40:00'),
(4, 3, 'Assigned staging IAM role with least privilege policy.', 0, '2026-10-16 16:30:00'),
(6, 2, 'Repaired Microsoft Office COM add-in registry key. Tested with John.', 0, '2026-10-17 12:45:00'),
(9, 2, 'Physical inspection completed. IT training conducted for user on company policy.', 1, '2026-10-18 11:30:00');

-- Audit Logs
INSERT INTO audit_logs (user_id, action, target_type, target_id, ip_address, details, created_at) VALUES
(1, 'SYSTEM_INIT', 'system', NULL, '127.0.0.1', 'OpsLens platform schema initialized', '2026-09-01 08:00:00'),
(4, 'USER_LOGIN_SUCCESS', 'user', 4, '192.168.1.45', 'Requester John Doe authenticated', '2026-10-15 09:00:00'),
(4, 'TICKET_CREATED', 'ticket', 1, '192.168.1.45', 'Created ticket: Corporate VPN Gateway Timeout', '2026-10-15 09:12:00'),
(2, 'TICKET_ASSIGNED', 'ticket', 1, '192.168.1.20', 'Sarah assigned ticket to self', '2026-10-15 09:20:00'),
(5, 'TICKET_CREATED', 'ticket', 2, '192.168.1.88', 'Created critical ticket: Suspicious phishing email', '2026-10-15 11:05:00'),
(3, 'TICKET_STATUS_CHANGED', 'ticket', 4, '192.168.1.22', 'Changed status from open to resolved', '2026-10-16 16:30:00'),
(1, 'USER_ROLE_UPDATED', 'user', 2, '127.0.0.1', 'Verified permissions for Sarah Support', '2026-10-17 08:00:00');

