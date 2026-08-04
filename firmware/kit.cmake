# The terminal-explorer kit, as one include.
#
# Include this file FIRST in a CMakeLists, before project(). It sets
# the board (RP2350B, tt_dbv3), the platform, and imports the
# pico-sdk. The extension pattern is:
#
#   cmake_minimum_required(VERSION 3.13)
#   include(<path-to-kit>/firmware/kit.cmake)
#   project(my_project C CXX ASM)
#   pico_sdk_init()
#   tt_extension(tt_host src/my_ext.c)
#
# See docs/extending.md for the full pattern.

list(APPEND PICO_BOARD_HEADER_DIRS ${CMAKE_CURRENT_LIST_DIR}/boards)
set(PICO_BOARD tt_dbv3 CACHE STRING "Board type")
set(PICO_PLATFORM rp2350-arm-s CACHE STRING "Platform")

include(${CMAKE_CURRENT_LIST_DIR}/pico_sdk_import.cmake)

set(TT_CORE_DIR ${CMAKE_CURRENT_LIST_DIR})
set(TT_CORE_MAIN ${TT_CORE_DIR}/src/main.c)

# Create the tt_core library. Guarded, so it runs once, and lazy, so
# it runs after project() and pico_sdk_init(). tt_extension() calls
# it for you. Call it yourself only to build a custom main:
#
#   tt_core_library()
#   add_executable(my_host src/my_main.c ...)
#   target_link_libraries(my_host tt_core)
function(tt_core_library)
    if(TARGET tt_core)
        return()
    endif()
    add_library(tt_core STATIC
        ${TT_CORE_DIR}/src/commands.c
        ${TT_CORE_DIR}/src/clock.c
        ${TT_CORE_DIR}/src/board.c
        ${TT_CORE_DIR}/src/trace.c
    )
    target_include_directories(tt_core PUBLIC ${TT_CORE_DIR}/include)
    target_link_libraries(tt_core
        pico_stdlib
        hardware_pio
        hardware_dma
    )
endfunction()

# One call builds a tt_host-style firmware: the kit's main plus your
# sources, linked against tt_core, USB stdio, uf2 output. Add extra
# pico libraries afterward with a normal target_link_libraries line.
function(tt_extension target)
    tt_core_library()
    add_executable(${target} ${TT_CORE_MAIN} ${ARGN})
    target_link_libraries(${target} tt_core)
    pico_enable_stdio_usb(${target} 1)
    pico_enable_stdio_uart(${target} 0)
    pico_add_extra_outputs(${target})
endfunction()
