"""Command-line interface for Central Knowledge Base."""

import argparse
import logging
import sys
from pathlib import Path
from typing import Optional

from central_knowledge_base.config import load_config, Config
from central_knowledge_base.api import run_server
from central_knowledge_base.connectors.confluence import ConfluenceConnector
from central_knowledge_base.connectors.jira import JiraConnector
from central_knowledge_base.connectors.git import GitConnector
from central_knowledge_base.graph import KnowledgeGraph
from central_knowledge_base.rag import VectorStore, RAGPipeline

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def cmd_run(args):
    """Run the API server."""
    try:
        config = load_config(args.config)
        logger.info(f"Starting server on {config.api.host}:{config.api.port}")
        run_server(
            host=config.api.host,
            port=config.api.port,
            debug=config.api.debug
        )
    except Exception as e:
        logger.error(f"Failed to start server: {e}")
        sys.exit(1)


def cmd_sync(args):
    """Sync data from external sources."""
    try:
        config = load_config(args.config)
        
        # Initialize knowledge graph
        knowledge_graph = KnowledgeGraph(config.graph)
        if not args.fresh:
            knowledge_graph.load()
        
        # Initialize vector store
        vector_store = VectorStore(config.vector_store)
        
        total_docs = 0
        total_entities = 0
        total_relations = 0
        
        # Sync from specified sources
        if 'confluence' in args.sources and config.confluence.enabled:
            logger.info("Syncing from Confluence")
            connector = ConfluenceConnector(config.confluence)
            
            if connector.test_connection():
                result = connector.sync()
                
                knowledge_graph.add_documents(result.documents)
                knowledge_graph.add_entities(result.entities)
                knowledge_graph.add_relationships(result.relationships)
                vector_store.add_documents(result.documents)
                
                total_docs += len(result.documents)
                total_entities += len(result.entities)
                total_relations += len(result.relationships)
                
                logger.info(f"Confluence sync completed: {len(result.documents)} docs, {len(result.entities)} entities")
            else:
                logger.error("Confluence connection test failed")
        
        if 'jira' in args.sources and config.jira.enabled:
            logger.info("Syncing from Jira")
            connector = JiraConnector(config.jira)
            
            if connector.test_connection():
                result = connector.sync()
                
                knowledge_graph.add_documents(result.documents)
                knowledge_graph.add_entities(result.entities)
                knowledge_graph.add_relationships(result.relationships)
                vector_store.add_documents(result.documents)
                
                total_docs += len(result.documents)
                total_entities += len(result.entities)
                total_relations += len(result.relationships)
                
                logger.info(f"Jira sync completed: {len(result.documents)} docs, {len(result.entities)} entities")
            else:
                logger.error("Jira connection test failed")
        
        if 'git' in args.sources and config.git.enabled:
            logger.info("Syncing from Git repositories")
            connector = GitConnector(config.git)
            
            if connector.test_connection():
                result = connector.sync(max_files=args.max_files, max_commits=args.max_commits)
                
                knowledge_graph.add_documents(result.documents)
                knowledge_graph.add_entities(result.entities)
                knowledge_graph.add_relationships(result.relationships)
                vector_store.add_documents(result.documents)
                
                total_docs += len(result.documents)
                total_entities += len(result.entities)
                total_relations += len(result.relationships)
                
                logger.info(f"Git sync completed: {len(result.documents)} docs, {len(result.entities)} entities")
            else:
                logger.error("Git connection test failed")
        
        # Discover implicit relationships
        if total_entities > 0:
            logger.info("Computing entity embeddings and discovering relationships")
            knowledge_graph.compute_entity_embeddings()
            implicit_relations = knowledge_graph.discover_implicit_relationships()
            knowledge_graph.add_relationships(implicit_relations)
            total_relations += len(implicit_relations)
            logger.info(f"Discovered {len(implicit_relations)} implicit relationships")
        
        # Save knowledge graph
        knowledge_graph.save()
        
        logger.info(f"Sync completed: {total_docs} documents, {total_entities} entities, {total_relations} relationships")
        
    except Exception as e:
        logger.error(f"Sync failed: {e}")
        sys.exit(1)


def cmd_query(args):
    """Query the knowledge base."""
    try:
        config = load_config(args.config)
        
        # Initialize components
        knowledge_graph = KnowledgeGraph(config.graph)
        if not knowledge_graph.load():
            logger.error("No knowledge graph found. Run 'ckb sync' first.")
            sys.exit(1)
        
        vector_store = VectorStore(config.vector_store)
        rag_pipeline = RAGPipeline(config.llm, vector_store, knowledge_graph)
        
        # Execute query
        logger.info(f"Querying: {args.question}")
        result = rag_pipeline.query(args.question)
        
        # Display results
        print(f"\nQuestion: {result.question}")
        print(f"Confidence: {result.confidence:.2f}")
        print(f"\nAnswer:\n{result.answer}")
        
        if result.sources:
            print(f"\nSources:")
            for i, source in enumerate(result.sources, 1):
                print(f"{i}. {source['title']} ({source['source_type']})")
                if source.get('url'):
                    print(f"   URL: {source['url']}")
                print(f"   Relevance: {source.get('relevance_score', 0):.2f}")
        
        if args.verbose:
            print(f"\nMetadata:")
            for key, value in result.metadata.items():
                print(f"  {key}: {value}")
        
    except Exception as e:
        logger.error(f"Query failed: {e}")
        sys.exit(1)


def cmd_stats(args):
    """Show knowledge base statistics."""
    try:
        config = load_config(args.config)
        
        # Initialize knowledge graph
        knowledge_graph = KnowledgeGraph(config.graph)
        if not knowledge_graph.load():
            logger.error("No knowledge graph found. Run 'ckb sync' first.")
            sys.exit(1)
        
        # Get statistics
        stats = knowledge_graph.get_statistics()
        
        print("Knowledge Graph Statistics:")
        print(f"  Documents: {stats['total_documents']}")
        print(f"  Entities: {stats['total_entities']}")
        print(f"  Relationships: {stats['total_relationships']}")
        print(f"  Graph Density: {stats['graph_density']:.4f}")
        print(f"  Connected Components: {stats['connected_components']}")
        print(f"  Has Embeddings: {'Yes' if stats['has_embeddings'] else 'No'}")
        
        print(f"\nEntity Types:")
        for entity_type, count in stats['entity_types'].items():
            print(f"  {entity_type}: {count}")
        
        print(f"\nRelationship Types:")
        for rel_type, count in stats['relationship_types'].items():
            print(f"  {rel_type}: {count}")
        
        print(f"\nSource Types:")
        for source_type, count in stats['source_types'].items():
            print(f"  {source_type}: {count}")
        
        # Vector store stats
        try:
            vector_store = VectorStore(config.vector_store)
            vs_stats = vector_store.get_statistics()
            print(f"\nVector Store Statistics:")
            print(f"  Documents: {vs_stats['total_documents']}")
            print(f"  Embedding Model: {vs_stats['embedding_model']}")
        except Exception as e:
            logger.warning(f"Could not get vector store stats: {e}")
        
    except Exception as e:
        logger.error(f"Failed to get statistics: {e}")
        sys.exit(1)


def cmd_test_connections(args):
    """Test connections to external sources."""
    try:
        config = load_config(args.config)
        
        results = {}
        
        # Test Confluence
        if config.confluence.enabled:
            try:
                connector = ConfluenceConnector(config.confluence)
                results['confluence'] = connector.test_connection()
            except Exception as e:
                logger.error(f"Confluence test failed: {e}")
                results['confluence'] = False
        
        # Test Jira
        if config.jira.enabled:
            try:
                connector = JiraConnector(config.jira)
                results['jira'] = connector.test_connection()
            except Exception as e:
                logger.error(f"Jira test failed: {e}")
                results['jira'] = False
        
        # Test Git
        if config.git.enabled:
            try:
                connector = GitConnector(config.git)
                results['git'] = connector.test_connection()
            except Exception as e:
                logger.error(f"Git test failed: {e}")
                results['git'] = False
        
        # Display results
        print("Connection Test Results:")
        for source, success in results.items():
            status = "✓ Connected" if success else "✗ Failed"
            print(f"  {source}: {status}")
        
        # Exit with error if any connection failed
        if not all(results.values()):
            sys.exit(1)
        
    except Exception as e:
        logger.error(f"Connection test failed: {e}")
        sys.exit(1)


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Central Knowledge Base - RAG application with external connectors"
    )
    parser.add_argument(
        '--config', '-c',
        default='config/config.yaml',
        help='Configuration file path'
    )
    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='Enable verbose output'
    )
    
    subparsers = parser.add_subparsers(dest='command', help='Available commands')
    
    # Run command
    run_parser = subparsers.add_parser('run', help='Run the API server')
    
    # Sync command
    sync_parser = subparsers.add_parser('sync', help='Sync data from external sources')
    sync_parser.add_argument(
        '--sources',
        nargs='+',
        choices=['confluence', 'jira', 'git'],
        default=['confluence', 'jira', 'git'],
        help='Sources to sync from'
    )
    sync_parser.add_argument(
        '--fresh',
        action='store_true',
        help='Start with a fresh knowledge graph'
    )
    sync_parser.add_argument(
        '--max-files',
        type=int,
        default=1000,
        help='Maximum files per Git repository'
    )
    sync_parser.add_argument(
        '--max-commits',
        type=int,
        default=100,
        help='Maximum commits per Git repository'
    )
    
    # Query command
    query_parser = subparsers.add_parser('query', help='Query the knowledge base')
    query_parser.add_argument('question', help='Question to ask')
    
    # Stats command
    stats_parser = subparsers.add_parser('stats', help='Show knowledge base statistics')
    
    # Test connections command
    test_parser = subparsers.add_parser('test', help='Test connections to external sources')
    
    args = parser.parse_args()
    
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    # Route to appropriate command handler
    if args.command == 'run':
        cmd_run(args)
    elif args.command == 'sync':
        cmd_sync(args)
    elif args.command == 'query':
        cmd_query(args)
    elif args.command == 'stats':
        cmd_stats(args)
    elif args.command == 'test':
        cmd_test_connections(args)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == '__main__':
    main()