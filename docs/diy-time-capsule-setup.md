# Disk Formatting and Configuration
For optimal disk setup and partitioning, see [Disk Formatting for Time Machine](disk-formatting-for-time-machine.md).
# DIY Time Capsule: Ubuntu + Samba Setup

## 1. Install Ubuntu
- Download and install the latest Ubuntu Server or Desktop.
- Update packages:
  ```
  sudo apt update && sudo apt upgrade
  ```

## 2. Install Required Utilities
- Install Samba and SSH:
  ```
  sudo apt install samba avahi-daemon openssh-server
  ```

## 3. Configure Samba for Time Capsule
- Edit Samba config:
  ```
  sudo vim /etc/samba/smb.conf
  ```
- Add a share section:
  ```
  [TimeCapsule]
  path = /srv/timecapsule
  browseable = yes
  guest ok = no
  read only = no
  vfs objects = fruit
  fruit:time machine = yes
  fruit:advertise_fullsync = true
  ```
- Create the share directory:
  ```
  sudo mkdir -p /srv/timecapsule
  sudo chown nobody:nogroup /srv/timecapsule
  sudo chmod 777 /srv/timecapsule
  ```

## 4. Set Up Samba User
- Create a user for backups:
  ```
  sudo smbpasswd -a <username>
  ```

## 5. Restart Services
- Restart Samba and Avahi:
  ```
  sudo systemctl restart smbd nmbd avahi-daemon
  ```

## 6. Connect from macOS
- Open Finder → Go → Connect to Server: `smb://<ubuntu-server-ip>/TimeCapsule`
- Authenticate with Samba user credentials.
- Select the share as a Time Machine destination in System Preferences.

## 7. Verify Backups
- Start a backup from macOS.
- Confirm files appear in `/srv/timecapsule`.

---

### What is avahi-daemon?

`avahi-daemon` is a service that implements mDNS (Multicast DNS) and DNS-SD (Service Discovery), also known as "Bonjour" on macOS. It allows your Ubuntu server to advertise the Time Machine share so Macs can discover it automatically in the network. Without Avahi, you may need to manually enter the server address on the Mac. For Time Machine over Samba, Avahi is recommended for seamless detection and connection.
