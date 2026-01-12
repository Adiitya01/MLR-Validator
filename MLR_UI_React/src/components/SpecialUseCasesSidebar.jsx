import React, { useState } from "react";
import "../styles/Auth.css";

const SpecialUseCasesSidebar = ({ collapsed, onClose, onDrugsClick }) => {
  return (
    <aside className={`special-sidebar${collapsed ? " collapsed" : ""}`}>
      <div className="sidebar-header">
        {!collapsed && <span>Special Use Cases</span>}
        <button className="sidebar-toggle-btn" onClick={onClose} title={collapsed ? "Expand" : "Collapse"}>
          {collapsed ? "◀" : "✖"}
        </button>
      </div>
      {!collapsed && (
        <div className="sidebar-section">
          <p className="sidebar-label">Validation Types</p>
          <button
            className="menu-item"
            onClick={onDrugsClick}
            style={{ fontSize: '16px', fontWeight: '600' }}
          >
            <span>Antibiotics Validation</span>
          </button>
        </div>
      )}
    </aside>
  );
};

export default SpecialUseCasesSidebar;
