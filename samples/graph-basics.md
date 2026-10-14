# Graphs and breadth-first search

These original notes are provided for testing ConceptFlow.

## Graph representations

A graph consists of vertices and edges. An undirected edge connects two vertices in both directions. A directed edge has a direction. An adjacency list stores the neighbours of each vertex. An adjacency matrix stores connections in a two-dimensional table.

For a graph with V vertices and E edges, an adjacency list requires O(V + E) space. An adjacency matrix requires O(V squared) space. A sparse graph has relatively few edges.

## Breadth-first search

Breadth-first search (BFS) explores vertices level by level. It uses a first-in, first-out queue. Mark a vertex visited when it is enqueued to avoid scheduling it repeatedly.

1. Mark the start vertex visited and enqueue it.
2. Remove a vertex from the front of the queue.
3. Inspect its neighbours. Mark each unvisited neighbour visited and enqueue it.
4. Repeat until the queue is empty.

With an adjacency list, BFS takes O(V + E) time. In an unweighted graph, BFS finds shortest paths measured by the number of edges. It does not generally find the minimum-weight path in a weighted graph.

## Worked example

Edges: A-B, A-C, B-D, C-E. Starting at A and visiting neighbours in alphabetical order gives BFS order A, B, C, D, E. The distance from A to D is two edges: A-B-D.

## Depth-first search

Depth-first search (DFS) explores one branch deeply before returning to other branches. It uses a stack, either explicitly or through recursive calls. BFS uses a queue; DFS uses a stack.

## Revision questions

Which data structure does BFS use? A queue.
When should BFS mark a vertex visited? When the vertex is enqueued.
What is the adjacency-list time complexity of BFS? O(V + E).
How many edges are in the shortest path from A to D in the example? Two.
