from typing import Optional
from pydantic import BaseModel


class TransactionRecord(BaseModel):
    地址: str
    行政區: str
    交易標的: str
    建物型態: str
    格局: str
    樓層: str
    總樓層: str
    建物面積_坪: Optional[float] = None
    總價_萬: Optional[float] = None
    單價_萬坪: Optional[float] = None
    屋齡建成: str
    交易日期: str

    model_config = {"populate_by_name": True}

    def to_display(self) -> dict:
        return {
            "地址": self.地址,
            "行政區": self.行政區,
            "交易標的": self.交易標的,
            "建物型態": self.建物型態,
            "格局": self.格局,
            "樓層": self.樓層,
            "總樓層": self.總樓層,
            "建物面積(坪)": self.建物面積_坪,
            "總價(萬)": self.總價_萬,
            "單價(萬/坪)": self.單價_萬坪,
            "屋齡建成": self.屋齡建成,
            "交易日期": self.交易日期,
        }


class DistrictStats(BaseModel):
    城市: str
    行政區: str
    統計筆數: int
    均價_萬坪: Optional[float] = None
    最高單價_萬坪: Optional[float] = None
    最低單價_萬坪: Optional[float] = None
    平均總價_萬: Optional[float] = None
    最近成交案例: list[dict] = []

    def to_display(self) -> dict:
        return {
            "城市": self.城市,
            "行政區": self.行政區,
            "統計筆數": self.統計筆數,
            "均價(萬/坪)": self.均價_萬坪,
            "最高單價(萬/坪)": self.最高單價_萬坪,
            "最低單價(萬/坪)": self.最低單價_萬坪,
            "平均總價(萬)": self.平均總價_萬,
            "最近成交案例": self.最近成交案例,
        }
