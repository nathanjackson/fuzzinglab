#include <assert.h>
#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>

int main(int argc, char** argv)
{
    uint8_t buf[3];
    int tmp;
    FILE* f = NULL;

    if (2 > argc) {
        printf("usage: %s PAYLOAD\n", argv[0]);
        return 1;
    }

    f = fopen(argv[1], "rb");
    if (!f) {
        fprintf(stderr, "could not open file\n");
        return 2;
    }

    tmp = fread(buf, 1, 3, f);
    if (tmp < 3) {
        fprintf(stderr, "too few bytes read from file\n");
        return 3;
    }

    if ('b' == buf[0]) {
        if ('u' == buf[1]) {
            if ('g' == buf[2]) {
                fprintf(stderr, "you found it!\n");
                abort();
            }
        }
    }

    return 0;
}