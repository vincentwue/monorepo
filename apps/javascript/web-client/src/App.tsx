import React from "react";
import { useSelector, useDispatch } from "react-redux";
import { MongoExplorer } from "@monorepo/mongo-explorer";
import { addIdea, RootState } from "@monorepo/store";

export default function App() {
  const dispatch = useDispatch();
  const ideas = useSelector((state: RootState) => state.ideas.items);

  return (
    <div style={{ padding: 30 }}>
      <h1>Ideas</h1>
      <button onClick={() => dispatch(addIdea("New idea"))}>Add Idea</button>
      <ul>
        {ideas.map((i, idx) => (
          <li key={idx}>{i}</li>
        ))}
      </ul>
      <MongoExplorer />
    </div>
  );
}
