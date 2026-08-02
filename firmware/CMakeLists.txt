cmake_minimum_required(VERSION 3.13)

include(preamble.cmake)

project(tt_terminal_explorer C CXX ASM)
set(CMAKE_C_STANDARD 11)

pico_sdk_init()

include(core.cmake)

add_executable(tt_host ${TT_CORE_MAIN})

target_link_libraries(tt_host tt_core)

pico_enable_stdio_usb(tt_host 1)
pico_enable_stdio_uart(tt_host 0)

pico_add_extra_outputs(tt_host)
