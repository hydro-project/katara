#include "set.h"

set* test_init_state() {
  set* out = set_create();
  return out;
}

set* test_next_state(set* state, int add, int value) {
  if (add == 1) {
    state = set_add(state, value);
  } else {
    state = set_remove(state, value);
  }
  
  return state;
}

int test_response(set* state, int value) {
  return set_contains(state, value);
}
