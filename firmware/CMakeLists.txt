cmake_minimum_required(VERSION 3.13)

include(preamble.cmake)

project(tt_terminal_explorer C CXX ASM)
set(CMAKE_C_STANDARD 11)

pico_sdk_init()

include(core.cmake)

tt_extension(tt_host)
