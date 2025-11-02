import { skipToken } from "@reduxjs/toolkit/query";
import React, { useEffect, useState } from "react";
import {
  useListCollectionsQuery,
  useListDatabasesQuery,
} from "./api";

type Connection = {
  alias: string;
  uri: string;
};

const STORAGE_KEY = "mongoConnections";

function loadConnections(): Connection[] {
  try {
    return JSON.parse(localStorage.getItem(STORAGE_KEY) ?? "[]");
  } catch {
    return [];
  }
}

function saveConnections(conns: Connection[]) {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(conns));
}

export const MongoExplorer: React.FC = () => {
  const [connections, setConnections] = useState<Connection[]>(loadConnections());
  const [selectedAlias, setSelectedAlias] = useState<string | null>(null);
  const [selectedDb, setSelectedDb] = useState<string | null>(null);
  const [newAlias, setNewAlias] = useState("");
  const [newUri, setNewUri] = useState("");

  // persist whenever updated
  useEffect(() => saveConnections(connections), [connections]);

  const selectedConn = connections.find((c) => c.alias === selectedAlias);

  const { data: databases = [], isLoading: loadingDbs } =
    useListDatabasesQuery(selectedConn ? selectedConn.alias : skipToken);

  const { data: collections = [], isLoading: loadingColls } =
    useListCollectionsQuery(
      selectedConn && selectedDb
        ? { alias: selectedConn.alias, db: selectedDb }
        : skipToken
    );

  const addConnection = () => {
    const alias = newAlias.trim();
    const uri = newUri.trim();  // 👈 important
    if (!alias || !uri) return;
    if (connections.some((c) => c.alias === alias)) {
      alert("Alias already exists!");
      return;
    }
    setConnections([...connections, { alias, uri }]);
    setNewAlias("");
    setNewUri("");
  };


  const removeConnection = (alias: string) => {
    setConnections(connections.filter((c) => c.alias !== alias));
    if (selectedAlias === alias) setSelectedAlias(null);
  };

  return (
    <div style={{ padding: 24 }}>
      <h1>Mongo Explorer</h1>

      {/* --- Manage connections --- */}
      <section>
        <h2>Connections</h2>
        <div style={{ display: "flex", gap: 8, marginBottom: 12 }}>
          <input
            placeholder="Alias (e.g. default)"
            value={newAlias}
            onChange={(e) => setNewAlias(e.target.value)}
          />
          <input
            placeholder="mongodb://localhost:27017"
            value={newUri}
            onChange={(e) => setNewUri(e.target.value)}
            style={{ flex: 1 }}
          />
          <button onClick={addConnection}>Add</button>
        </div>

        {connections.length === 0 ? (
          <p>No connections saved.</p>
        ) : (
          <ul>
            {connections.map(({ alias }) => (
              <li key={alias}>
                <button onClick={() => setSelectedAlias(alias)}>{alias}</button>
                <button onClick={() => removeConnection(alias)}>✕</button>
              </li>
            ))}
          </ul>
        )}
      </section>

      {/* --- Databases --- */}
      {selectedAlias && (
        <section>
          <h2>Databases ({selectedAlias})</h2>
          {loadingDbs ? (
            <p>Loading...</p>
          ) : (
            <ul>
              {databases.map((db: string) => (
                <li key={db}>
                  <button onClick={() => setSelectedDb(db)}>{db}</button>
                </li>
              ))}
            </ul>
          )}
        </section>
      )}

      {/* --- Collections --- */}
      {selectedAlias && selectedDb && (
        <section>
          <h2>
            Collections ({selectedAlias} → {selectedDb})
          </h2>
          {loadingColls ? (
            <p>Loading...</p>
          ) : (
            <ul>
              {collections.map((c: string) => (
                <li key={c}>{c}</li>
              ))}
            </ul>
          )}
        </section>
      )}
    </div>
  );
};
