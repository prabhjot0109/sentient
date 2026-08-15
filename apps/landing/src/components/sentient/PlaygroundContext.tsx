import React, { createContext, useContext, useState, type ReactNode } from "react";

type PlaygroundContextType = {
  isOpen: boolean;
  activeCharacterId: string;
  openPlayground: (characterId?: string) => void;
  closePlayground: () => void;
};

const PlaygroundContext = createContext<PlaygroundContextType | undefined>(undefined);

export function PlaygroundProvider({ children }: { children: ReactNode }) {
  const [isOpen, setIsOpen] = useState(false);
  const [activeCharacterId, setActiveCharacterId] = useState("skyrim-guard");

  const openPlayground = (characterId?: string) => {
    if (characterId) {
      setActiveCharacterId(characterId);
    }
    setIsOpen(true);
  };

  const closePlayground = () => {
    setIsOpen(false);
  };

  return (
    <PlaygroundContext.Provider
      value={{ isOpen, activeCharacterId, openPlayground, closePlayground }}
    >
      {children}
    </PlaygroundContext.Provider>
  );
}

export function usePlayground() {
  const context = useContext(PlaygroundContext);
  if (!context) {
    throw new Error("usePlayground must be used within a PlaygroundProvider");
  }
  return context;
}
