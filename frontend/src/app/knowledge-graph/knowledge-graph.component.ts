import { Component, signal, inject, OnInit } from "@angular/core";
import { FFlowModule } from "@foblex/flow";
import { KnowledgeGraphService, GraphNode, GraphEdge } from "./knowledge-graph.service";
import { NodeComponent } from "./components/node/node.component";

@Component(
    {
        selector: "app-knowledge-graph",
        templateUrl: "./knowledge-graph.component.html",
        styleUrls: ["./knowledge-graph.component.scss"],
        imports: [
            FFlowModule,
            NodeComponent
        ]
    }
)
export class KnowledgeGraphComponent implements OnInit {
    private readonly graphService = inject(KnowledgeGraphService);
    
    nodes = signal<GraphNode[]>([]);
    edges = signal<GraphEdge[]>([]);
    isLoading = signal(false);

    async ngOnInit() {
        await this.loadGraph();
    }

    async loadGraph() {
        this.isLoading.set(true);
        try {
            const data = await this.graphService.fetchGraph();
            this.nodes.set(data.nodes);
            this.edges.set(data.edges);
        } finally {
            this.isLoading.set(false);
        }
    }

    getNodePosition(index: number): { x: number, y: number } {
        // Simple layout: arrange nodes in a grid
        const cols = 4;
        const spacing = 250;
        const row = Math.floor(index / cols);
        const col = index % cols;
        return {
            x: 50 + col * spacing,
            y: 50 + row * spacing
        };
    }
}