# Security & Lockdown Guide

## Protection Levels

### Level 1: File Permissions (Basic)
**Difficulty:** Easy
**Protection:** Prevents casual viewing
**Reversible:** Yes (with sudo)

```bash
chmod +x lockdown.sh
sudo ./lockdown.sh
```

**What it does:**
- Creates dedicated `klyra` user
- Makes code read-only for klyra user only
- Hides config.json from other users
- Protects conversation storage

**Pros:**
- Easy to implement
- Doesn't break updates
- Can undo if needed

**Cons:**
- Root users can still read
- Determined users can bypass

---

### Level 2: Compile to Bytecode (Medium)
**Difficulty:** Medium
**Protection:** Code is obfuscated
**Reversible:** Partially (bytecode can be decompiled)

```bash
chmod +x compile_code.sh
./compile_code.sh
```

**What it does:**
- Compiles Python to `.pyc` bytecode
- Removes source `.py` files
- Creates backup before deletion

**Pros:**
- Source code not readable
- Harder to modify
- Still runs normally

**Cons:**
- Can be decompiled (with effort)
- Breaks auto-updates (no more .py files)
- Need backup for development

---

### Level 3: Full Encryption (Advanced)
**Difficulty:** Hard
**Protection:** Very strong
**Reversible:** No (without key)

Use PyArmor or similar tools to encrypt Python code.

**Not implemented** - Adds complexity and breaks debugging.

---

## Recommended Approach

**For most users: Level 1 (File Permissions)**

This provides good protection without breaking functionality:

1. Run the installer: `./install_service.sh`
2. Run lockdown: `sudo ./lockdown.sh`
3. Auto-updates still work!

**Benefits:**
- ✅ Casual users can't browse code
- ✅ Config file hidden
- ✅ Auto-updates still work
- ✅ Easy to undo: `sudo chmod -R 755 /home/pi/klyramachine`

---

## Additional Security Tips

### 1. Disable SSH Password Login
```bash
sudo nano /etc/ssh/sshd_config
# Set: PasswordAuthentication no
sudo systemctl restart ssh
```

### 2. Hide Raspberry Pi on Network
```bash
# Disable mDNS/Bonjour
sudo systemctl disable avahi-daemon
sudo systemctl stop avahi-daemon
```

### 3. Firewall (UFW)
```bash
sudo apt install ufw
sudo ufw default deny incoming
sudo ufw default allow outgoing
sudo ufw enable
```

### 4. Disable Unused Services
```bash
sudo systemctl disable bluetooth
sudo systemctl disable cups
```

### 5. Read-Only Filesystem (Advanced)
Make SD card read-only to prevent tampering:
```bash
# Follow guides for read-only Raspberry Pi OS
# Warning: Makes system harder to update
```

---

## Security vs Usability

**Remember:**
- More security = Harder to update and debug
- Lockdown AFTER you've tested everything works
- Keep your GitHub repo private if code is sensitive
- Auto-updates require write access (conflicts with full lockdown)

**Balanced approach:**
1. Use file permissions (Level 1)
2. Keep GitHub repo private
3. Disable SSH password login
4. Enable firewall
