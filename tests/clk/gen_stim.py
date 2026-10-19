import random
import sys

random.seed(int(sys.argv[2]) if len(sys.argv) > 2 else 1)
lines = ["0 0", "0 1", "0 1"]
reset_left = 0
mrdy_left = 0
mrdy = 1
for _ in range(int(sys.argv[1]) if len(sys.argv) > 1 else 400):
    if reset_left == 0 and random.random() < 0.02:
        reset_left = random.randint(1, 3)
    if mrdy_left == 0 and random.random() < 0.15:
        mrdy_left = random.randint(1, 5)
        mrdy = 1 - mrdy
    reset = 0 if reset_left else 1
    if reset_left:
        reset_left -= 1
    if mrdy_left:
        mrdy_left -= 1
        if mrdy_left == 0:
            mrdy = 1
    lines.append("%d %d" % (reset, mrdy))
print("\n".join(lines))
