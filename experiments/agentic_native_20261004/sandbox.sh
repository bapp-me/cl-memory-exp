#!/bin/sh
# A separate read-only archive sandbox for native memory commands.
set -eu
root="$1"
work="$2"
corpus="$3"
audit="$4"
mount --make-rprivate /
mount -t tmpfs -o size=256m,nosuid tmpfs "$root"
mkdir -p "$root/usr" "$root/work" "$root/memory" "$root/tmp" "$root/dev" "$root/etc"
mount --rbind /usr "$root/usr"
mount -o remount,bind,ro /usr "$root/usr"
ln -s usr/bin "$root/bin"
ln -s usr/lib "$root/lib"
ln -s usr/lib64 "$root/lib64"
mount --bind "$work" "$root/work"
mount --bind "$corpus" "$root/memory"
mount -o remount,bind,ro "$root/memory"
touch "$root/dev/null" "$root/dev/urandom"
mount --bind /dev/null "$root/dev/null"
mount --bind /dev/urandom "$root/dev/urandom"
printf 'sandbox:x:0:0:sandbox:/work:/bin/bash\n' > "$root/etc/passwd"
printf 'sandbox:x:0:\n' > "$root/etc/group"
ulimit -t 25
ulimit -f 2048
ulimit -n 128
ulimit -v 524288
cd "$root"
# The tracer opens its log outside the chroot. The agent cannot read or change that file.
exec /usr/bin/strace -f -qq -yy -s 4096 -e trace=%file,clone,clone3,fork,vfork -o "$audit" \
  env -i PATH=/usr/bin:/bin HOME=/work TMPDIR=/tmp LC_ALL=C.UTF-8 \
  /usr/bin/prlimit --nproc=64 -- /usr/sbin/chroot "$root" \
  /usr/bin/setpriv --bounding-set=-all --no-new-privs /usr/bin/timeout --kill-after=2s 30s \
  /bin/bash --noprofile --norc /work/command.sh
