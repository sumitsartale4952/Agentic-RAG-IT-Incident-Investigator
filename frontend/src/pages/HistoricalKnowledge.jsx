import { useEffect, useState } from "react";
import { BookOpen, Database, Search, SearchCheck } from "lucide-react";
import { useOutletContext } from "react-router-dom";
import PageHeader from "../components/common/PageHeader.jsx";
import DataUnavailable from "../components/common/DataUnavailable.jsx";
import StatusBadge from "../components/common/StatusBadge.jsx";
import { getErrorMessage, getRAGStatus, searchHistoricalIncidents } from "../services/api.js";

export default function HistoricalKnowledge() {
  const [status, setStatus] = useState(null);
  const [statusError, setStatusError] = useState("");
  const [query, setQuery] = useState("");
  const [results, setResults] = useState([]);
  const [searchError, setSearchError] = useState("");
  const [searching, setSearching] = useState(false);
  const { notify } = useOutletContext();

  async function loadStatus() {
    try {
      setStatus(await getRAGStatus());
      setStatusError("");
    } catch (error) {
      setStatus(null);
      setStatusError(getErrorMessage(error));
    }
  }
  useEffect(() => { loadStatus(); }, []);

  async function search(event) {
    event.preventDefault();
    if (!query.trim()) {
      notify({ type: "error", message: "Enter a search query before retrieving historical incidents." });
      return;
    }
    setSearching(true);
    try {
      const response = await searchHistoricalIncidents({ query: query.trim() });
      setResults((Array.isArray(response) ? response : Array.isArray(response?.results) ? response.results : Array.isArray(response?.documents) ? response.documents : []).filter(Boolean));
      setSearchError("");
    } catch (error) {
      setResults([]);
      setSearchError(getErrorMessage(error));
    } finally {
      setSearching(false);
    }
  }

  const documents = Array.isArray(status?.documents) ? status.documents : Array.isArray(status?.items) ? status.items : [];
  return (
    <main className="page-content">
      <PageHeader eyebrow="RETRIEVAL AUGMENTED GENERATION" title="Historical knowledge" description="Review indexed incident knowledge and test retrieval against the connected collection." />
      {statusError && <DataUnavailable message={statusError} onRetry={loadStatus} />}
      <section className="knowledge-status-grid">
        <article className="panel knowledge-stat"><span className="knowledge-icon"><BookOpen size={17} /></span><small>Documents indexed</small><strong>{status?.document_count ?? status?.total_documents ?? "—"}</strong></article>
        <article className="panel knowledge-stat"><span className="knowledge-icon purple"><BookOpen size={17} /></span><small>Embedding model</small><strong>{status?.embedding_model || "Unavailable"}</strong></article>
        <article className="panel knowledge-stat"><span className="knowledge-icon purple"><Database size={17} /></span><small>Vector database</small><strong>{status?.vector_database || status?.vector_store || "Unavailable"}</strong><StatusBadge status={status?.vector_database_status || "unavailable"} label={status?.vector_database_status || "Status unavailable"} /></article>
        <article className="panel knowledge-stat"><span className="knowledge-icon teal"><Database size={17} /></span><small>Collection</small><strong>{status?.collection_name || "Unavailable"}</strong></article>
        <article className="panel knowledge-stat"><span className="knowledge-icon orange"><BookOpen size={17} /></span><small>Ingestion status</small><StatusBadge status={status?.ingestion_status || "unavailable"} label={status?.ingestion_status || "Unavailable"} /></article>
      </section>
      <section className="panel retrieval-panel">
        <div className="panel-heading"><div><h2>Test retrieval</h2><p>Results, scores, and snippets come exclusively from the backend.</p></div><span className="retrieval-icon"><SearchCheck size={17} /></span></div>
        <form className="retrieval-form" onSubmit={search}><label className="search-field"><Search size={16} /><input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="e.g. database connection timeout and high latency" /></label><button className="button button-primary" type="submit" disabled={searching}>{searching ? "Searching…" : "Search knowledge"}</button></form>
        {searchError && <DataUnavailable message={searchError} />}
        {results.length > 0 && <div className="historical-list">{results.map((doc, index) => <article className="historical-item" key={doc.id || doc.incident_id || index}><div className="knowledge-result-header"><strong>{doc.title || doc.incident_id || "Retrieved document"}</strong><span>{doc.similarity_score ?? doc.score ?? "Score unavailable"}</span></div><small>Incident {doc.incident_id || "not provided"} · {doc.service || doc.service_name || "—"} · {doc.severity || "—"}</small><p>{doc.snippet || doc.text || doc.content || "No matching text returned."}</p><small>Root cause {doc.root_cause ? "available" : "not provided"}</small></article>)}</div>}
        {!results.length && !searchError && <div className="retrieval-empty">Submit a query to test the configured historical search endpoint.</div>}
      </section>
      <section className="panel list-panel">
        <div className="panel-heading"><div><h2>Indexed documents</h2><p>Document availability is confirmed by RAG status response.</p></div><span>{documents.length} returned</span></div>
        {documents.length ? <div className="historical-list">{documents.map((doc, index) => <article className="historical-item" key={doc.id || index}><strong>{doc.title || doc.incident_id || "Historical incident"}</strong><p>{doc.preview || doc.snippet || "No preview provided."}</p><small>{doc.service || "Service unavailable"} · {doc.severity || "Severity unavailable"}</small></article>)}</div> : <div className="retrieval-empty">{status ? "No documents were returned by the backend." : "Document status unavailable. No indexed count is assumed."}</div>}
      </section>
    </main>
  );
}
