#ifndef OTA_JOBS_TOPIC_H
#define OTA_JOBS_TOPIC_H

#include <stdbool.h>
#include <stddef.h>
#include <string.h>

/* AWS Jobs events use a job ID, rather than the thing-scoped Jobs API topics. */
static inline bool otaJobs_BuildCancellationTopic(char * output, size_t capacity,
                                                 const char * jobId, size_t jobIdLength,
                                                 size_t * outputLength)
{
    static const char prefix[] = "$aws/events/job/";
    static const char suffix[] = "/cancellation_in_progress";
    size_t index;
    size_t required;
    if (outputLength == NULL) { return false; }
    *outputLength = 0U;
    if ((output == NULL) || (capacity == 0U)) { return false; }
    output[0] = '\0';
    if ((jobId == NULL) || (jobIdLength == 0U) || (jobIdLength > 64U)) { return false; }
    for (index = 0U; index < jobIdLength; index++)
    {
        unsigned char value = (unsigned char)jobId[index];
        if (!(((value >= 'a') && (value <= 'z')) || ((value >= 'A') && (value <= 'Z')) ||
              ((value >= '0') && (value <= '9')) || (value == '-') || (value == '_')))
        {
            return false;
        }
    }
    required = (sizeof(prefix) - 1U) + jobIdLength + (sizeof(suffix) - 1U);
    if (required >= capacity) { return false; }
    memcpy(output, prefix, sizeof(prefix) - 1U);
    memcpy(output + sizeof(prefix) - 1U, jobId, jobIdLength);
    memcpy(output + sizeof(prefix) - 1U + jobIdLength, suffix, sizeof(suffix));
    *outputLength = required;
    return true;
}

#endif
