import React from "react";
import { BrowserRouter, Route, Routes } from "react-router-dom";
import { RequireAuth } from "@monorepo/auth";
import { TopBarLayout } from "@monorepo/topbar-layout";

const ExamplePage = ({ title }: { title: string }) => (
  <div className="flex h-full items-center justify-center text-xl text-white">
    {title}
  </div>
);

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route
          path="/*"
          element={
            <RequireAuth redirectTo="http://localhost:5173/login?return_to=http://localhost:5147/">
              <TopBarLayout>
                <Routes>
                  <Route path="/" element={<ExamplePage title="Dashboard" />} />
                  <Route path="/ideas" element={<ExamplePage title="Ideas" />} />
                </Routes>
              </TopBarLayout>
            </RequireAuth>
          }
        />
      </Routes>
    </BrowserRouter>
  );
}
