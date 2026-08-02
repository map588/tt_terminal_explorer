#pragma once

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

/* One protocol command. A handler returns NULL for success (its
 * payload, if any, in tt_reply[]) or a short error token. */
struct cmd {
    const char *name;
    const char *(*fn)(int argc, char **argv);
    const char *help;
};

/* Handlers put their "ok" payload here. */
#define TT_REPLY_CAP 96
extern char tt_reply[TT_REPLY_CAP];

/* Argument and bus helpers, shared with extensions. */
bool parse_u32(const char *s, uint32_t *out);
bool parse_hex8(const char *s, uint8_t *out);
uint8_t read_byte(unsigned base);

/* Read and execute protocol commands from USB CDC. Does not return. */
void command_loop(void);
