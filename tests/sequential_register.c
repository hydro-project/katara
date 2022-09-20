int test_init_state() {
  return 0;
}

int test_next_state(int state, int value, int clock) {
  state = value;
  return state;
}

int test_response(int state) {
  return state;
}
