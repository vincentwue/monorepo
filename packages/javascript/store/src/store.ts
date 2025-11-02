import { mongoApi } from "@monorepo/mongo-explorer";
import { configureStore, createSlice, PayloadAction } from "@reduxjs/toolkit";
import ideasReducer from "./features/ideasSlice";

export const store = configureStore({
  reducer: {
    ideas: ideasReducer,
    mongoApi: mongoApi.reducer,
  },
  middleware: (getDefaultMiddleware) =>
    getDefaultMiddleware().concat(mongoApi.middleware),
});

export type RootState = ReturnType<typeof store.getState>;
export type AppDispatch = typeof store.dispatch;

interface IdeaState {
  items: string[];
}

const initialState: IdeaState = {
  items: [],
};

const ideasSlice = createSlice({
  name: "ideas",
  initialState,
  reducers: {
    addIdea(state, action: PayloadAction<string>) {
      state.items.push(action.payload);
    },
  },
});

export const { addIdea } = ideasSlice.actions;
export default ideasSlice.reducer;
