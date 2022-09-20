int test_init_state() {
  int out = 0;
  return out;
}

int test_next_state(int state, int add, int node_id) {
  if (add == 1) {
    state = state + 1;
  } else {
    state = state - 1;
  }
  
  return state;
}

int test_response(int state) {
  return state;
}
