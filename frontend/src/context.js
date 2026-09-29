import { createContext } from "react";

export const ActiveStatementContext = createContext({
  activeStatementId: null,
  setActiveStatementId: () => {},
  refreshCounter: 0,
  triggerRefresh: () => {},
});
