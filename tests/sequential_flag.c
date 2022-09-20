int test_init_state() {
  return 0;
}

int test_next_state(int state, int enable, int clock) {
  if (enable == 1) {
    return 1;
  } else {
    return 0;
  }
}

int test_response(int state) {
  return state;
}
