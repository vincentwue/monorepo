import "redux";

declare module "@monorepo/store" {
  // Import the actual reducer function to infer its return type
  type UiState = ReturnType<typeof import("../ui/uiSlice").default>;

  interface RootState {
    ui?: UiState;
  }
}
