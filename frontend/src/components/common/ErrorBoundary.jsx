import { Component } from "react";
import { AlertTriangle, RotateCcw } from "lucide-react";

export default class ErrorBoundary extends Component {
  constructor(props) {
    super(props);
    this.state = { error: null };
  }

  static getDerivedStateFromError(error) {
    return { error };
  }

  render() {
    if (!this.state.error) return this.props.children;
    return (
      <main className="fatal-error">
        <span className="fatal-icon"><AlertTriangle size={22} /></span>
        <h1>Something went wrong</h1>
        <p>The page encountered an unexpected error. Your other workspace areas are unaffected.</p>
        <button className="button button-secondary" onClick={() => window.location.reload()}>
          <RotateCcw size={15} /> Reload page
        </button>
      </main>
    );
  }
}
