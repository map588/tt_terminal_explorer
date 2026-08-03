# Core firmware library for the Tiny Tapeout demo board.
#
# Include this file AFTER pico_sdk_init(), from this repo's own
# build or from an extension project:
#
#   include(<path-to-kit>/firmware/core.cmake)
#   tt_extension(tt_host src/my_ext.c)
#
# See docs/extending.md for the full pattern.

set(TT_CORE_DIR ${CMAKE_CURRENT_LIST_DIR})
set(TT_CORE_MAIN ${TT_CORE_DIR}/src/main.c)

add_library(tt_core STATIC
    ${TT_CORE_DIR}/src/commands.c
    ${TT_CORE_DIR}/src/clock.c
    ${TT_CORE_DIR}/src/board.c
)

target_include_directories(tt_core PUBLIC ${TT_CORE_DIR}/include)

target_link_libraries(tt_core
    pico_stdlib
    hardware_pio
)

# One call builds a tt_host-style firmware: the kit's main plus your
# sources, linked against tt_core, USB stdio, uf2 output. Add extra
# pico libraries afterward with a normal target_link_libraries line.
# To replace the main instead, use add_executable with your own main
# and link tt_core yourself (TT_CORE_MAIN stays available).
function(tt_extension target)
    add_executable(${target} ${TT_CORE_MAIN} ${ARGN})
    target_link_libraries(${target} tt_core)
    pico_enable_stdio_usb(${target} 1)
    pico_enable_stdio_uart(${target} 0)
    pico_add_extra_outputs(${target})
endfunction()
