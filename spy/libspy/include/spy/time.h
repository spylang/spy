#ifndef SPY_TIME_H
#define SPY_TIME_H

#include <time.h>

#ifdef SPY_TARGET_WASI
#include <unistd.h>
#endif

static inline double
spy_time$time(void) {
    struct timespec ts;
    clock_gettime(CLOCK_REALTIME, &ts);
    return (double)ts.tv_sec + (double)ts.tv_nsec / 1e9;
}

static inline void
spy_time$sleep(double seconds) {
    struct timespec req;
    req.tv_sec = (time_t)seconds;
    req.tv_nsec = (long)((seconds - req.tv_sec) * 1e9);
    nanosleep(&req, NULL);
}

#endif /* SPY_TIME_H */
