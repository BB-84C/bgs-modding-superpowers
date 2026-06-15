/** Recursive argument walkers shared by pipeline safety rules. */
export interface StringArg {
    key: string;
    path: string;
    value: string;
}
export declare function walkStringArgs(value: unknown, path?: string, key?: string): Generator<StringArg>;
