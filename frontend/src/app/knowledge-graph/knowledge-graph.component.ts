import { Component } from "@angular/core";
import { FFlowModule } from "@foblex/flow";

@Component(
    {
        selector: "app-knowledge-graph",
        templateUrl: "./knowledge-graph.component.html",
        styleUrls: ["./knowledge-graph.component.scss"],
        imports: [
            FFlowModule
        ]
    }
)
export class KnowledgeGraphComponent {
    // Component logic goes here
}