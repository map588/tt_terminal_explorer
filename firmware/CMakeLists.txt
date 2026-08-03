cmake_minimum_required(VERSION 3.13)

include(kit.cmake)

project(tt_terminal_explorer C CXX ASM)
set(CMAKE_C_STANDARD 11)

pico_sdk_init()

tt_extension(tt_host)
