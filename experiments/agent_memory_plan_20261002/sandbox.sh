#!/bin/sh
# Invoked ONLY within unshare -Urnmpf. No host home, repository, network or keys.
set -eu
root="$1"
work="$2"
deps="$3"
python_root="$4"
shift 4
mount --make-rprivate /
mount -t tmpfs -o size=256m,nosuid tmpfs "$root"
mkdir -p "$root/usr" "$root/work" "$root/tmp" "$root/dev" "$root/etc" "$root/deps" "$root/python"
mount --rbind /usr "$root/usr"
mount -o remount,bind,ro /usr "$root/usr"
ln -s usr/bin "$root/bin"
ln -s usr/lib "$root/lib"
ln -s usr/lib64 "$root/lib64"
mount --bind "$work" "$root/work"
mount --bind "$deps" "$root/deps"
mount -o remount,bind,ro "$root/deps"
mount --bind "$python_root" "$root/python"
mount -o remount,bind,ro "$root/python"
touch "$root/dev/null" "$root/dev/urandom"
mount --bind /dev/null "$root/dev/null"
mount --bind /dev/urandom "$root/dev/urandom"
printf 'sandbox:x:0:0:sandbox:/work:/bin/sh\n' > "$root/etc/passwd"
printf 'sandbox:x:0:\n' > "$root/etc/group"
ulimit -t 90
ulimit -f 131072
ulimit -n 128
ulimit -v 3145728
cd "$root"
exec env -i PATH=/python/bin:/usr/bin:/bin HOME=/work TMPDIR=/tmp PYTHONPATH=/deps PYTHONDONTWRITEBYTECODE=1 OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MPLCONFIGDIR=/tmp/mpl \
  /usr/bin/prlimit --nproc=64 -- /usr/sbin/chroot "$root" /usr/bin/setpriv --bounding-set=-all --no-new-privs "$@"
