#ifndef CONFIG_COMMAND_VALUE_H
#define CONFIG_COMMAND_VALUE_H

#include <stddef.h>
#include <string.h>

/* The conf set protocol owns the complete value after command/action/key.
 * PEM text and escaped newlines are data, not additional CLI parameters. */
static inline const char * Cli_ConfigValueTail(const char * command, size_t * length)
{
    const char * cursor = command;
    unsigned int word;
    if (length == NULL) { return NULL; }
    *length = 0U;
    if (cursor == NULL) { return NULL; }
    for (word = 0U; word < 3U; word++)
    {
        while (*cursor == ' ') { cursor++; }
        if (*cursor == '\0') { return NULL; }
        while ((*cursor != '\0') && (*cursor != ' ')) { cursor++; }
    }
    while (*cursor == ' ') { cursor++; }
    if (*cursor == '\0') { return NULL; }
    *length = strlen(cursor);
    return cursor;
}

/* Reserve the final byte outside the length supplied to the OSS interpreter. */
static inline size_t Cli_TerminateOutput(char * buffer, size_t capacity)
{
    if ((buffer == NULL) || (capacity == 0U)) { return 0U; }
    buffer[capacity - 1U] = '\0';
    return strlen(buffer);
}

/* The maintenance image only accepts public signer entries. It must not expose
 * existing client/private credential readback through the generic conf handler. */
static inline int Cli_PublicSignerCommandAllowed(const char * command)
{
    const char * words[4];
    size_t lengths[4];
    unsigned int index;
    const char * cursor = command;
    if (cursor == NULL) { return 0; }
    for (index = 0U; index < 4U; index++)
    {
        while (*cursor == ' ') { cursor++; }
        words[index] = cursor;
        while ((*cursor != '\0') && (*cursor != ' ')) { cursor++; }
        lengths[index] = (size_t)(cursor - words[index]);
    }
    if ((lengths[0] != 4U) || (memcmp(words[0], "conf", 4U) != 0)) { return 0; }
    if ((lengths[1] == 6U) && (memcmp(words[1], "commit", 6U) == 0))
    {
        return lengths[2] == 0U;
    }
    if ((lengths[1] != 3U) ||
        ((memcmp(words[1], "get", 3U) != 0) && (memcmp(words[1], "set", 3U) != 0))) { return 0; }
    if (!(((lengths[2] == 12U) && (memcmp(words[2], "codesigncert", 12U) == 0)) ||
          ((lengths[2] == 14U) && (memcmp(words[2], "codesignpubkey", 14U) == 0)))) { return 0; }
    return (memcmp(words[1], "set", 3U) == 0) ? (lengths[3] != 0U) : (lengths[3] == 0U);
}

#endif
