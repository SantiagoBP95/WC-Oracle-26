import { useQuery } from "@tanstack/react-query";
import { createContext, useContext, useState, type ReactNode } from "react";

import { api } from "../api/client";

export interface ModelInfo {
  name: string;
  label: string;
  available: boolean;
  has_run: boolean;
}

interface ModelCtx {
  model: string;
  setModel: (m: string) => void;
  models: ModelInfo[];
}

const Ctx = createContext<ModelCtx>(null as unknown as ModelCtx);

export const useModel = () => useContext(Ctx);

export function ModelProvider({ children }: { children: ReactNode }) {
  const [model, setModelState] = useState<string>(() => localStorage.getItem("wc_model") || "elo");
  const { data: models = [] } = useQuery({
    queryKey: ["models"],
    queryFn: async () => (await api.get<ModelInfo[]>("/simulations/models")).data,
  });

  function setModel(m: string) {
    localStorage.setItem("wc_model", m);
    setModelState(m);
  }

  return <Ctx.Provider value={{ model, setModel, models }}>{children}</Ctx.Provider>;
}
