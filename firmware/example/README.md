# Example extension

This directory is a complete extension firmware. It adds one
command, `blink <n>`, on top of the kit core. Use it two ways.

## Build and try it

```sh
cmake -S firmware/example -B build-example
cmake --build build-example
```

Flash `build-example/tt_host.uf2` (hold BOOTSEL, copy the file).
Then open the serial port and type:

```
help        # the core commands plus blink
blink 3     # the board LED blinks three times, reply: ok 3
```

## Start your own project from it

1. Copy this directory into your repo.
2. Add the kit as a git submodule, for example at `kit/`.
3. In `CMakeLists.txt`, point the include at the submodule:
   `kit/firmware/kit.cmake`.
4. Rename `blink_ext.c` and put your commands in it.

`docs/extending.md` in the kit describes the other hooks: run code
at boot, react to clock or design changes, add reply fields.
