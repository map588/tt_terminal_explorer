# Core firmware library for the Tiny Tapeout demo board.
#
# Include this file AFTER pico_sdk_init(), from this repo's own
# build or from an extension project:
#
#   include(<path-to-kit>/firmware/core.cmake)
#   add_executable(tt_host ${TT_CORE_MAIN} src/my_ext.c)
#   target_link_libraries(tt_host tt_core)
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
