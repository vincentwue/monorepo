import { createSlice, PayloadAction } from "@reduxjs/toolkit";

interface IdeaState {
  items: string[];
}

const initialState: IdeaState = {
  items: []
};

const ideasSlice = createSlice({
  name: "ideas",
  initialState,
  reducers: {
    addIdea(state, action: PayloadAction<string>) {
      state.items.push(action.payload);
    }
  }
});

export const { addIdea } = ideasSlice.actions;
export default ideasSlice.reducer;
