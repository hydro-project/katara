#include <stdbool.h>

typedef struct set {} set;

set* set_create();
set* set_add(set* s, int x);
set* set_remove(set* s, int x);
int set_contains(set* s, int v);
