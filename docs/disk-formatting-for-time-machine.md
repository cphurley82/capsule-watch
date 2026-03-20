# Disk Formatting and Configuration for Time Machine on Ubuntu

## 1. Choose a Disk
- Use a dedicated physical disk or large partition for Time Machine backups.
- Prefer SSD or high-quality HDD for reliability.

## 2. Partition and Format
- Use `lsblk` to identify the disk:
  ```
  lsblk
  ```
- Partition with `fdisk` or `parted`:
  ```
  sudo fdisk /dev/sdX
  ```
- Format as ext4 (recommended for Linux):
  ```
  sudo mkfs.ext4 -L TimeCapsule /dev/sdX1
  ```

## 3. Mount the Disk
- Create a mount point:
  ```
  sudo mkdir -p /srv/timecapsule
  ```
- Add to `/etc/fstab` for automatic mounting:
  ```
  UUID=<disk-uuid> /srv/timecapsule ext4 defaults,noatime 0 2
  ```
- Find UUID:
  ```
  sudo blkid /dev/sdX1
  ```
- Mount:
  ```
  sudo mount /srv/timecapsule
  ```

## 4. Set Permissions
- Ensure Samba user can write:
  ```
  sudo chown nobody:nogroup /srv/timecapsule
  sudo chmod 777 /srv/timecapsule
  ```

## 5. Optional: Sparsebundle Setup
- Time Machine uses sparsebundles for each Mac. No manual setup needed, but ensure the share supports large files.

## 6. Quota Configuration (Optional)
- To limit backup size, use Samba's `fruit:quota` or filesystem quotas.
- Example for Samba:
  ```
  fruit:quota = 500000000000
  ```
- For ext4, use `quota` tools:
  ```
  sudo apt install quota
  sudo edquota -u <username>
  ```

## 7. Best Practices
- Use `noatime` mount option to reduce disk writes.
- Monitor SMART status for drive health.
- Keep backups on a dedicated disk for easier recovery.

---

For detailed steps, see the official Ubuntu and Samba documentation. This guide is linked from the main DIY Time Capsule setup doc for optimal disk configuration.