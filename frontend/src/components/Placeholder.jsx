export function Placeholder({ title, icon: Icon }) {
  return (
    <section className="workspace" style={{ display: "flex", alignItems: "center", justifyContent: "center" }}>
      <div style={{ textAlign: "center", color: "#999" }}>
        <Icon size={48} style={{ margin: "0 auto 16px", opacity: 0.4 }} />
        <h2>{title}</h2>
        <p>功能开发中，敬请期待</p>
      </div>
    </section>
  );
}
