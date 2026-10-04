from typing import Any, Iterable, Literal, Optional, TypeAlias, Union, overload

from psycopg import sql
from psycopg.abc import Params, Query
from psycopg.sql import Composed
from psycopg_pool import AsyncConnectionPool
from pydantic import BaseModel

from ..exceptions import (
    PostgresConfigurationError,
    PostgresTypeError,
    PostgresValueError,
)
from .pool import get_pool

DatabaseRow: TypeAlias = dict[str, Any]


class PostgreSQL:
    def __init__(self, *, table: Optional[str] = None):
        self.table = table

    @property
    def pool(self) -> Optional[AsyncConnectionPool]:
        return get_pool()

    @property
    def table(self) -> Optional[str]:
        return self._table

    @table.setter
    def table(self, value: Optional[str]):
        self._table = value

    @property
    def current_timestamp(self) -> str:
        return "now()"

    async def _do_execute(self, conn, query: Query, params: Optional[Params]) -> int:
        async with conn.cursor() as cursor:
            await cursor.execute(query, params)
            return cursor.rowcount or 0

    async def execute(self, query: Query, params: Optional[Params] = None, *, conn: Union[Any, None] = None) -> int:
        if conn:
            return await self._do_execute(conn, query, params)
        else:
            async with self.pool.connection() as conn:  # type: ignore
                return await self._do_execute(conn, query, params)

    @overload
    async def fetch(self, query: Query, params: Optional[Params] = None, *, one: bool = True) -> dict: ...

    @overload
    async def fetch(self, query: Query, params: Optional[Params] = None, *, one: bool = False) -> list[dict]: ...

    async def fetch(self, query: Query, params: Optional[Params] = None, *, one: bool = False) -> Optional[Union[dict, list[dict]]]:
        async with self.pool.connection() as conn:  # type: ignore
            async with conn.cursor() as cur:
                await cur.execute(query, params)
                if one:
                    return await cur.fetchone()  # type: ignore
                return await cur.fetchall()  # type: ignore

    @staticmethod
    def _construct_returning_clause(returning: Optional[Union[list[str], Literal["*"]]]) -> Union[sql.SQL, Composed]:
        if not returning:
            return sql.SQL("")

        if returning == "*":
            return sql.SQL("RETURNING *")

        if len(returning) > 1 and "*" in returning:
            raise PostgresValueError("You cannot pass `*` in a list for `returning` parameter")

        return sql.SQL("RETURNING {}").format(sql.SQL(", ").join(map(sql.Identifier, returning)))

    def _remove_id_column(self, rows: list[DatabaseRow]) -> list[DatabaseRow]:
        for row in rows:
            row.pop("id", None)

        return rows

    @overload
    async def _do_insert(
        self,
        conn,
        insert_query: Composed,
        parameter_values: list,
        returning: Union[list[str], Literal["*"]],
        rows_to_insert: list[DatabaseRow],
    ) -> list[DatabaseRow]:
        """
        Overload for when the user specifies what to return upon inserting a new row
        """

        pass

    @overload
    async def _do_insert(
        self, conn, insert_query: Composed, parameter_values: list, returning: None, rows_to_insert: list[DatabaseRow]
    ) -> int:
        """
        Overload for when the user does not specify what to return upon inserting a new row
        """

        pass

    async def _do_insert(
        self,
        conn,
        insert_query: Composed,
        parameter_values: list,
        returning: Optional[Union[list[str], Literal["*"]]],
        rows_to_insert: list[DatabaseRow],
    ) -> Union[list[DatabaseRow], int]:
        async with conn.cursor() as cursor:
            await cursor.execute(insert_query, parameter_values)
            if not returning:
                return len(rows_to_insert)
            return await cursor.fetchall()

    @overload
    async def insert(
        self, rows: Union[DatabaseRow, Iterable[DatabaseRow]], *, returning: Union[list[str], Literal["*"]], conn: Union[Any, None] = None
    ) -> list[DatabaseRow]:
        """
        Overload for when the user specifies what to return upon inserting a new row
        """

        pass

    @overload
    async def insert(
        self, rows: Union[DatabaseRow, Iterable[DatabaseRow]], *, returning: None = None, conn: Union[Any, None] = None
    ) -> int:
        """
        Overload for when the user does not specify what to return upon inserting a new row
        """

        pass

    async def insert(
        self,
        rows: Union[DatabaseRow, Iterable[DatabaseRow]],
        *,
        returning: Optional[Union[list[str], Literal["*"]]] = None,
        conn: Union[Any, None] = None,
    ) -> Union[list[DatabaseRow], int]:
        if self.table is None:
            raise PostgresConfigurationError(
                "Table name is not configured! You must configure it through `table` property to be able to insert."
            )

        if isinstance(rows, dict):
            rows_to_insert = [rows]
        else:
            rows_to_insert = list(rows)

        rows_to_insert = self._remove_id_column(rows_to_insert)  # type: ignore
        if not rows_to_insert:
            return 0

        column_names: list[str] = list(rows_to_insert[0].keys())
        columns_placeholders = sql.SQL(", ").join(sql.Placeholder() for _ in column_names)
        rows_groups = [sql.SQL("({})").format(columns_placeholders) for _ in rows_to_insert]

        insert_query = sql.SQL("INSERT INTO {table} ({columns}) VALUES {values} {returning_clause};").format(
            table=sql.Identifier(self.table),
            columns=sql.SQL(", ").join(map(sql.Identifier, column_names)),
            values=sql.SQL(", ").join(rows_groups),
            returning_clause=self._construct_returning_clause(returning),
        )

        parameter_values = []
        for row in rows_to_insert:
            parameter_values.extend(row[col] for col in column_names)

        if not conn:
            async with self.pool.connection() as conn:  # type: ignore
                return await self._do_insert(conn, insert_query, parameter_values, returning, rows_to_insert)
        else:
            return await self._do_insert(conn, insert_query, parameter_values, returning, rows_to_insert)


class Repository(PostgreSQL):
    Schema: type[BaseModel]

    def __init__(self, *, table: Optional[str] = None):
        super().__init__(table=table)

        if not hasattr(self, "Schema"):
            raise PostgresTypeError(f"{self.__class__.__name__} must define `Schema` class")

        if not issubclass(self.Schema, BaseModel):
            raise PostgresTypeError("Schema must inherit from `pydantic.BaseModel`")

    @overload
    async def insert(
        self, rows: Union[DatabaseRow, Iterable[DatabaseRow]], *, returning: Union[list[str], Literal["*"]], conn: Union[Any, None] = None
    ) -> list[DatabaseRow]:
        """
        Overload for when the user specifies what to return upon inserting a new row
        """

        pass

    @overload
    async def insert(
        self, rows: Union[DatabaseRow, Iterable[DatabaseRow]], *, returning: None = None, conn: Union[Any, None] = None
    ) -> int:
        """
        Overload for when the user does not specify what to return upon inserting a new row
        """

        pass

    async def insert(
        self,
        rows: Union[DatabaseRow, Iterable[DatabaseRow]],
        *,
        returning: Optional[Union[list[str], Literal["*"]]] = None,
        conn: Union[Any, None] = None,
    ) -> Union[list[DatabaseRow], int]:
        if isinstance(rows, dict):
            validated = [self.Schema(**rows)]  # type: ignore
        else:
            validated = [self.Schema(**row) for row in rows]

        rows_dicts = [model.model_dump() for model in validated]
        return await super().insert(rows_dicts, returning=returning, conn=conn)


if __name__ == "__main__":
    pass
