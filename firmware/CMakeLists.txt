cmake_minimum_required(VERSION 3.13)

# Tiny Tapeout demo board v3 carries an RP2350B; see boards/tt_dbv3.h.
list(APPEND PICO_BOARD_HEADER_DIRS ${CMAKE_CURRENT_LIST_DIR}/boards)
set(PICO_BOARD tt_dbv3 CACHE STRING "Board type")
set(PICO_PLATFORM rp2350-arm-s CACHE STRING "Platform")

include(pico_sdk_import.cmake)

project(tt_terminal_explorer C CXX ASM)
set(CMAKE_C_STANDARD 11)

pico_sdk_init()

add_executable(tt_host
    src/main.c
    src/commands.c
    src/clock.c
    src/board.c
)

target_include_directories(tt_host PRIVATE include)

target_link_libraries(tt_host
    pico_stdlib
    hardware_pio
)

pico_enable_stdio_usb(tt_host 1)
pico_enable_stdio_uart(tt_host 0)

pico_add_extra_outputs(tt_host)
